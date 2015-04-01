angular.module('profileService', [
  ])



  .factory("ProfileService", function($http, $location){

    var data = {}

    function getProfile(slug){
      var url = "/profile/" + slug
      return $http.get(url).success(function(resp){
        data.profile = resp
      })
    }

    return {
      data: data,
      foo: function(){
        return "i am in the profile service"
      },

      createProfile: function(name, pmids) {
        console.log("i am making a profile:", name, pmids)
        var postData = {
          name: name,
          pmids: pmids
        }
        $http.post("/profile",postData)
          .success(function(resp, status, headers){
            console.log("yay got a resp from /profile!", resp)
            $location.path("/u/" + resp.slug)
          })
      },

      getProfile: getProfile
    }


  })